#!/usr/bin/env python3
# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
"""
Nx VMS REST Server API sample: log in to ONE site and save a still-frame
SNAPSHOT (not a video clip) from one or more devices.

Direct-to-server only, same auth flow as ../rest-list-cameras:

  1. Log in:    POST /rest/v4/login/sessions  {username, password}  -> {"token": ...}
  2. Snapshot:  GET  /rest/v4/devices/{id}/image  (Authorization: Bearer <token>)
                ?timestampMs=-1 (latest/live frame) &format=<fmt> [&size=<WxH>]
  3. Log out:   DELETE /rest/v4/login/sessions/<token>   (clean up the session)

--device-ids accepts one or several device ids, comma-separated. Each is
fetched and saved independently: one device failing (bad id, no permission,
...) is reported but does not stop the rest from being saved.

Connecting to the server:
  --host is the server, e.g. https://192.168.1.10:7001  (note the https + port).
  Local servers usually present a self-signed certificate, so for a lab server
  you will typically need --insecure.

Reference: https://meta.nxvms.com/doc/developers/api-tool/main?type=1
"""

import argparse
import datetime as dt
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

# Image formats exposed by this sample. The v4 endpoint also supports "raw"
# and "_auto"; left out here since they aren't standalone raster files.
FORMATS = ["jpg", "png", "tif"]
DEFAULT_FORMAT = "jpg"

_SIZE_RE = re.compile(r"^\d+x\d+$")
_DIGITS_RE = re.compile(r"^\d+$")


def parse_device_ids(raw):
    """Split a comma-separated device-id string into a non-empty list."""
    text = "" if raw is None else str(raw)
    ids = [part.strip() for part in text.split(",")]
    ids = [part for part in ids if part]
    if not ids:
        raise ApiError("--device-ids must contain at least one device id.")
    return ids


def parse_size(value):
    """Validate an optional --size WxH string. None/blank -> None (original size)."""
    if value is None or str(value).strip() == "":
        return None
    text = str(value).strip()
    if not _SIZE_RE.match(text):
        raise ApiError(
            f'--size must look like "WIDTHxHEIGHT" (got "{value}").')
    return text


def parse_snapshot_timestamp(value):
    """Turn the optional --at archive point into epoch ms, or None for live.

    Accepts an ISO 8601 string (2026-06-15T12:00:00Z) or a raw epoch-ms number.
    Empty/blank/None -> None (live). Naive times are treated as UTC.
    """
    text = "" if value is None else str(value).strip()
    if not text:
        return None  # live
    if _DIGITS_RE.match(text):
        return int(text)  # already epoch ms
    try:
        when = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ApiError(
            f'Could not parse --at "{text}". Use ISO time or epoch ms.') from exc
    if when.tzinfo is None:
        when = when.replace(tzinfo=dt.timezone.utc)
    return int(when.timestamp() * 1000)


def epoch_ms_to_datetime(ms):
    """Convert epoch milliseconds to a UTC datetime."""
    return dt.datetime.fromtimestamp(ms / 1000, tz=dt.timezone.utc)


def default_out_name(device_id, fmt, now=None):
    """Default output filename: snapshot-<device>-<ts>.<fmt> (filesystem-safe)."""
    now = now or dt.datetime.now(dt.timezone.utc)
    stamp = now.strftime("%Y-%m-%dT%H-%M-%S")
    safe_id = re.sub(r"[^A-Za-z0-9._-]", "_", str(device_id))
    return f"snapshot-{safe_id}-{stamp}.{fmt}"


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

    fmt = (pick(cli_args.format, "NX_SNAPSHOT_FORMAT") or DEFAULT_FORMAT).strip().lower()
    if fmt not in FORMATS:
        raise ApiError(f'Unsupported --format "{fmt}". Choose one of: '
                        f'{", ".join(FORMATS)}.')

    return {
        "host": pick(cli_args.host, "NX_SERVER_HOST"),
        "user": pick(cli_args.user, "NX_SERVER_USER"),
        "password": pick(cli_args.password, "NX_SERVER_PASSWORD"),
        "device_ids": device_ids,
        "format": fmt,
        "size": parse_size(pick(cli_args.size, "NX_SNAPSHOT_SIZE")),
        "out_dir": cli_args.out_dir or ".",
        "timestamp_ms": parse_snapshot_timestamp(cli_args.at),
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

    def get_device_image(self, device_id, fmt=DEFAULT_FORMAT, size=None,
                         timestamp_ms=None):
        """GET a single still frame from one device. Returns bytes.

        timestamp_ms=None means the latest/live frame (timestampMs=-1); a
        given value pulls the frame nearest that point in the archive.
        """
        from urllib.parse import quote, urlencode
        path = f"{self.host}{API}/devices/{quote(str(device_id), safe='')}/image"
        ts = -1 if timestamp_ms is None else timestamp_ms
        params = [("timestampMs", str(ts)), ("format", fmt)]
        if size:
            params.append(("size", size))
        url = f"{path}?{urlencode(params)}"
        try:
            response = self.session.get(
                url, headers=self._auth_header(), timeout=self.timeout)
        except requests.exceptions.RequestException as exc:
            raise ApiError(f"Could not reach {url}: {exc}") from exc
        if response.status_code in (401, 403):
            raise AuthError(
                f"Snapshot request unauthorized (HTTP {response.status_code}) "
                f"for device {device_id}.")
        if not response.ok:
            raise ApiError(f"Snapshot for device {device_id} failed: "
                           f"HTTP {response.status_code} {response.text[:200]}")
        return response.content

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
        description="Log in to one Nx VMS server and save a still-frame "
                    "snapshot from one or more devices.")
    parser.add_argument("--host", default=None,
                        help="Server URL, e.g. https://192.168.1.10:7001")
    parser.add_argument("--user", default=None, help="Local server username")
    parser.add_argument("--password", default=None, help="Local server password")
    parser.add_argument("--device-ids", default=None,
                        help="One or more device ids, comma-separated")
    parser.add_argument("--format", default=None, choices=FORMATS,
                        help=f"Image format, one of: {', '.join(FORMATS)} (default jpg)")
    parser.add_argument("--size", default=None,
                        help='Image size "WIDTHxHEIGHT" (default: original size)')
    parser.add_argument("--out-dir", default=None,
                        help="Directory to save snapshots into (default: current dir)")
    parser.add_argument("--at", default=None,
                        help="Archive point in time (ISO 8601 or epoch ms); "
                             "omit for the latest/live frame")
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

    snapshot_time = (epoch_ms_to_datetime(config["timestamp_ms"])
                     if config["timestamp_ms"] is not None else None)

    any_failed = False
    try:
        client.login()
        print(f"Logged in to {config['host']} as {config['user']}\n")
        for device_id in config["device_ids"]:
            out_path = os.path.join(
                config["out_dir"],
                default_out_name(device_id, config["format"], now=snapshot_time))
            try:
                image_bytes = client.get_device_image(
                    device_id, fmt=config["format"], size=config["size"],
                    timestamp_ms=config["timestamp_ms"])
                with open(out_path, "wb") as handle:
                    handle.write(image_bytes)
                print(f"{device_id}: wrote {len(image_bytes)} bytes to {out_path}")
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
