# REST Server API — Save a device snapshot (Python)

Connects to **one VMS server/site** and saves a still-frame **snapshot** from
one or more devices — the "just give me one image" counterpart to
[`../media-http-stream`](../media-http-stream), which saves a video clip.

```
Logged in to https://192.168.1.10:7001 as admin

{a1b2...}: wrote 84213 bytes to snapshot-a1b2..._-2026-06-15T12-00-00.jpg
{c3d4...}: wrote 91007 bytes to snapshot-c3d4..._-2026-06-15T12-00-01.jpg
```

## What the code does (Nx 5.0+ bearer-token auth)

1. **Log in** — `POST /rest/v4/login/sessions` with `{username, password}` → `{"token": ...}`.
2. **Snapshot each device** — `GET /rest/v4/devices/{id}/image` with
   `Authorization: Bearer <token>`, `timestampMs=-1` (the latest/live frame),
   `format=<jpg|png|tif>`, and an optional `size=WIDTHxHEIGHT`.
3. **Log out** — `DELETE /rest/v4/login/sessions/<token>` to release the session
   (done automatically, even if an error occurs).

Each device id is fetched independently: if one fails (bad id, no permission,
offline), it's reported and the rest still get saved. The process exits `1`
if any device failed, `0` if all succeeded, `2` for missing/bad configuration.

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

Uses the same `NX_SERVER_*` variables as `rest-list-cameras`, plus its own
"Device snapshot" block:

```bash
cp ../../.env.example ../../.env   # then edit the NX_SERVER_* / NX_DEVICE_IDS lines
```

- `NX_SERVER_HOST` — e.g. `https://192.168.1.10:7001` (include `https://` and
  the port), or a relay address `https://<siteId>.relay.vmsproxy.com`.
- `NX_SERVER_USER`, `NX_SERVER_PASSWORD` — a **local** server account.
- `NX_DEVICE_IDS` — one or more device ids, **comma-separated**, e.g.
  `id1,id2,id3`.
- `NX_SNAPSHOT_FORMAT` — `jpg`, `png`, or `tif`. Default `jpg`.
- `NX_SNAPSHOT_SIZE` — `WIDTHxHEIGHT`. Blank keeps the original resolution.

## Run

```bash
# Local servers almost always use a self-signed cert, so --insecure is normal here:
python rest_device_snapshot.py --env-file ../../.env --insecure

# Or fully on the command line, with several devices:
python rest_device_snapshot.py \
  --host https://192.168.1.10:7001 \
  --user admin \
  --password 'your-password' \
  --device-ids id1,id2,id3 \
  --format png --size 640x480 \
  --insecure

# A frame from the archive instead of live, at a specific point in time:
python rest_device_snapshot.py --env-file ../../.env --insecure \
  --device-ids id1 --at 2026-06-15T12:00:00Z
```

## CLI flags

| Flag | Default | Purpose |
|---|---|---|
| `--host` | — | Server URL, e.g. `https://192.168.1.10:7001` |
| `--user` / `--password` | — | Local server account |
| `--device-ids` | — | One or more device ids, comma-separated |
| `--format` | `jpg` | `jpg`, `png`, or `tif` |
| `--size` | original size | `WIDTHxHEIGHT`, e.g. `640x480` |
| `--at` | latest/live | Archive point in time: ISO 8601 (`2026-06-15T12:00:00Z`) or epoch ms |
| `--out-dir` | current directory | Where to write the snapshot files |
| `--env-file` | `.env` | Path to a `.env` file |
| `--insecure` | off | Skip TLS verification (self-signed lab certs) |

`--at` is CLI-only (no `.env`/env var) — an archive point in time is a
per-run choice, not persistent configuration.

Output filenames default to `snapshot-<device-id>-<timestamp>.<format>`, where
`<timestamp>` is the archive point given via `--at`, or the current time for a
live/latest snapshot.

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
| `--device-ids must contain at least one device id` | `--device-ids` was empty or only commas. | Pass at least one real id. |
| `--size must look like "WIDTHxHEIGHT"` | Malformed `--size`. | Use e.g. `640x480`. |

## Files

| File | Purpose |
|------|---------|
| `rest_device_snapshot.py` | The sample. Run it directly. |
| `test_rest_device_snapshot.py` | Offline tests (mocked HTTP). |
| `requirements.txt` | `requests` + `pytest`. |
