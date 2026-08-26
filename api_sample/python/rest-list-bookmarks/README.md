# REST Server API — List device bookmarks (Python)

Connects to **one VMS server/site** and lists **bookmarks** for one or more
devices, newest-created first — handy for "what's the latest bookmark on this
camera?" via `--limit 1`. Output is the full bookmark records as
pretty-printed JSON, exactly as the API returned them.

```
Logged in to https://192.168.1.10:7001 as admin

{a1b2...}:
[
  {
    "name": "Break-in",
    "description": "Rear door forced open",
    "startTimeMs": 1750000000000,
    "durationMs": 5000,
    "tags": ["security", "alert"],
    "id": "bm1_srv1"
  }
]
```

## What the code does (Nx 5.0+ bearer-token auth)

1. **Log in** — `POST /rest/v4/login/sessions` with `{username, password}` → `{"token": ...}`.
2. **List each device's bookmarks** — `GET /rest/v4/devices/{deviceId}/bookmarks`
   with `Authorization: Bearer <token>`. Always ordered `_orderBy=creationTimeMs&order=desc`
   (newest-created first), plus optional `startTimeMs`/`endTimeMs`/`limit`.
3. **Log out** — `DELETE /rest/v4/login/sessions/<token>` to release the session
   (done automatically, even if an error occurs).

Each device id is queried independently: if one fails (bad id, no
permission), it's reported and the rest still get listed. The process exits
`1` if any device failed, `0` if all succeeded, `2` for missing/bad
configuration.

This sample is **read-only** — creating, editing, deleting, or tagging
bookmarks isn't covered here.

## Prerequisites

- Python 3.8+
- Network access to an Nx VMS server and a **local** server account
  (username/password). Cloud users use a different login flow (see the note
  in [`../rest-list-cameras`](../rest-list-cameras)).
- The tests need neither a server nor a network.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Configure

Uses the same `NX_SERVER_*` / `NX_DEVICE_IDS` variables as `rest-device-snapshot`:

```bash
cp ../../.env.example ../../.env   # then edit the NX_SERVER_* / NX_DEVICE_IDS lines
```

- `NX_SERVER_HOST` — e.g. `https://192.168.1.10:7001` (include `https://` and
  the port), or a relay address `https://<siteId>.relay.vmsproxy.com`.
- `NX_SERVER_USER`, `NX_SERVER_PASSWORD` — a **local** server account.
- `NX_DEVICE_IDS` — one or more device ids, **comma-separated**, e.g.
  `id1,id2,id3`.

## Run

```bash
# Local servers almost always use a self-signed cert, so --insecure is normal here:
python rest_list_bookmarks.py --env-file ../../.env --insecure

# Just the single most recent bookmark on each device:
python rest_list_bookmarks.py --env-file ../../.env --insecure --limit 1

# Bookmarks within a time window, fully on the command line:
python rest_list_bookmarks.py \
  --host https://192.168.1.10:7001 \
  --user admin \
  --password 'your-password' \
  --device-ids id1,id2 \
  --start 2026-06-01T00:00:00Z --end 2026-06-30T00:00:00Z \
  --insecure
```

## CLI flags

| Flag | Default | Purpose |
|---|---|---|
| `--host` | — | Server URL, e.g. `https://192.168.1.10:7001` |
| `--user` / `--password` | — | Local server account |
| `--device-ids` | — | One or more device ids, comma-separated |
| `--start` | none | Only bookmarks at/after this time: ISO 8601 or epoch ms |
| `--end` | none | Only bookmarks at/before this time: ISO 8601 or epoch ms |
| `--limit` | none | Max bookmarks per device, e.g. `--limit 1` for just the latest |
| `--env-file` | `.env` | Path to a `.env` file |
| `--insecure` | off | Skip TLS verification (self-signed lab certs) |

`--start`/`--end`/`--limit` are CLI-only (no `.env`/env var) — a query window
is a per-run choice, not persistent configuration.

## Run the tests

```bash
pytest -v
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|--------|--------------|-----|
| `SSLError` / certificate verify failed | Local server uses a self-signed cert. | Add `--insecure` (expected for local servers). |
| `Could not reach https://...` | Wrong IP/port, server down, or firewall. | Confirm host + port `7001`, and that the server is reachable. |
| `Login unauthorized (HTTP 401/403)` | Wrong password, or this is a **cloud** user. | Use a local account. |
| `<id>: FAILED: ... HTTP 404 ...` | That device id doesn't exist on this site. | Check the id via `../rest-list-cameras`. |
| `[]` (empty array) | Genuinely no bookmarks in range, or account lacks permission. | Widen/remove `--start`/`--end`, check permissions in the Nx client. |
| `--limit must be a positive integer` | `--limit` was zero, negative, or not a number. | Use e.g. `--limit 5`. |

## Files

| File | Purpose |
|------|---------|
| `rest_list_bookmarks.py` | The sample. Run it directly. |
| `test_rest_list_bookmarks.py` | Offline tests (mocked HTTP). |
| `requirements.txt` | `requests` + `pytest`. |
