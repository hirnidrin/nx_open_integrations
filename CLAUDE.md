# CLAUDE.md

Nx Meta / Nx Witness open integration samples. Work on this repo **from inside
the dev container** — see [.devcontainer/README.md](.devcontainer/README.md) for
the full setup. The essentials:

## Environment

- Ubuntu 24.04, `python3` **3.12.3** — deliberately the same as the target Nx
  Witness server.
- A shared tool venv (`~/.venv-tools`: `requests`, `pytest`, `pytest-cov`,
  `ruff`, `ipython`) is already first on `PATH`. **Do not create a venv or
  `pip install` to run the tests** — `pytest` and `python3` are already the
  venv's. Ubuntu's system Python is externally managed (PEP 668); `pip` into it
  will refuse.
- Also available: `rg`, `jq`, `ffmpeg`/`ffprobe`, `ping`, `nc`.
- **Python only.** No Node, .NET, or C++ toolchain is installed. Don't try to
  build or test `api_sample/node_js`, `api_sample/typescript`,
  `api_sample/csharp`, or `cpp/` — read and edit them if asked, but say plainly
  that they can't be run here. Adding a toolchain is a `devcontainer.json`
  feature plus a rebuild.
- A server on the *host* is not `localhost` from in here — use
  `host.containers.internal` (Podman) / `host.docker.internal` (Docker). LAN IPs
  and the cloud relay work directly.

## Testing

Every Python sample ships an offline suite — no server, no account, no network:

```bash
pytest api_sample/python        # all of them, from the repo root
cd api_sample/python/<sample> && pytest -v   # just one
```

Tests import their sibling module by bare name (`import rest_list_cameras`),
which works from either location because the folders aren't packages. Keep it
that way: no `__init__.py`, no rootdir config file.

## Repo layout

| Path | |
|---|---|
| `api_sample/python/` | the samples in scope; one folder each, with sample + tests + README + `requirements.txt` |
| `api_sample/node_js/`, `typescript/`, `csharp/`, `javascript/`, `web/` | ports of the same samples in other languages |
| `api_sample/docs/` | API notes |
| `cpp/` | Nx SDK server plugins (Conan + SDK, not set up here) |
| `Cloud Service Checker/` | standalone cloud-reachability script |

## Python sample conventions

Documented in [api_sample/python/README.md](api_sample/python/README.md) — match
them when adding or editing a sample:

- One runnable `.py` with a `main()` and an `if __name__ == "__main__"` guard.
- Core logic takes an **injectable HTTP layer** so tests run fully offline
  against mocked responses. Preserve this — it's what makes the suites hermetic.
- `argparse`, with **CLI > env var > `.env`** precedence. Credentials are never
  hard-coded.
- `--insecure` skips TLS verification (self-signed lab certs); `--env-file`
  points at the shared `.env`.
- REST samples target **`/rest/v4`**.
- Every Python sample has a matching `node_js` port with identical behavior and
  matching tests; if you change behavior in one, the other is now out of sync —
  flag it. (Surface difference: Python `--env-file`, Node `--dotenv`.)
- MPL 2.0 header as the first line of each source file:
  `# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/`

## Secrets

Real credentials live in `api_sample/.env`, gitignored;
`api_sample/.env.example` is the committed template. Never write a credential
into a tracked file, a test, or a commit message.

## Git

- This fork (`hirnidrin/nx_open_integrations`) has `master` — tracking the
  current VMS dev version — and `playground`, where local work happens. The
  upstream Network Optix repo also carries `vms_5.0` / `vms_5.1` release
  branches; samples on `master` don't necessarily work against release VMS
  versions.
- Commit subjects carry the ticket: `VI-68: Add JSON-RPC sample`.
- Push and all GitHub work (PRs, issues) happen **on the host**, not in the
  container — there's no `gh` here, and `git push` is denied in the container's
  Claude settings.
- **Never run `git clean`.** Project memory that hasn't been committed yet sits
  untracked-but-not-ignored, and a plain `git clean -df` destroys it.

## Claude Code config

`CLAUDE_CONFIG_DIR` points at
[.devcontainer/claude-home/](.devcontainer/claude-home/) (container-scoped; a
session on the host sees none of it). Project memory lives in
`claude-home/projects/-workspaces-nx_open_integrations/memory/` and is meant to
be reviewed and committed like any other change. `claude-home/settings.json` is
shared with everyone who clones the repo — personal preferences belong in
`settings.local.json` next to it.
