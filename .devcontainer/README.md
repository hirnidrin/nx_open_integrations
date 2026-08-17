# Dev Container

This is the development environment for the Nx Witness / Nx Meta API integration
samples in this repo. The host needs only:

* [VS Code](https://code.visualstudio.com/)
* the [Dev Containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) extension
* [Docker](https://www.docker.com/) or [Podman](https://podman.io/)

There are deliberately no dev env specific tools on the host — everything runs
inside the container.

## What's in it

**Python only, for now.** The repo also holds Node, TypeScript, C# and C++
samples; none of their toolchains are installed. Adding Node later means adding
a feature to `devcontainer.json` — see [Adding a toolchain](#adding-a-toolchain).

The image is `mcr.microsoft.com/devcontainers/base:ubuntu-24.04`, chosen to
mirror the target Nx Witness server: apt's `python3` on noble is **3.12.3**, the
same interpreter the samples run under there. The base image ships no language
runtime, so [`post-create.sh`](post-create.sh) installs everything on create:

| | |
|---|---|
| `python3`, `python3-venv`, `python3-pip` | 3.12.3 from the noble archive |
| `ripgrep`, `jq` | fast code and JSON search |
| `ffmpeg` (incl. `ffprobe`) | inspect the clips `media-http-stream` saves; generate a test video for `virtual-camera-upload` |
| `iputils-ping`, `netcat-openbsd` | check the server is reachable before blaming a sample |
| Claude Code CLI | native install (no Node.js needed), lands in `~/.local/bin` |

No `gh`: GitHub work — pushing, PRs, issues — happens on the host, not in here.
Local `git` is available (it comes with the base image) for staging, committing
and reading history against the bind-mounted checkout.

### The shared tool venv

Ubuntu marks its system Python as externally managed (PEP 668), so `pip` cannot
install into it — the same constraint you hit on the server. `post-create.sh`
therefore creates one venv at `~/.venv-tools` from
[`requirements-dev.txt`](requirements-dev.txt) (`requests`, `pytest`,
`pytest-cov`, `ruff`, `ipython`) and `devcontainer.json` puts it first on `PATH`.
No `activate` step: `pytest` and `python3` in any terminal are already the venv's.

It lives in `$HOME`, outside the bind mount, so it never shows up in `git status`
and a rebuild recreates it. Run `bash .devcontainer/post-create.sh` by hand after
editing `requirements-dev.txt`.

This venv is for working *on* the repo. It does not replace the per-sample
`requirements.txt` files or the per-sample `.venv` flow the sample READMEs
document — that is what a *user* of the samples follows, and it still works
unchanged.

## How to start

1. Open the repo in VS Code.
1. Command Palette → **Dev Containers: Reopen in Container**.
1. The first build pulls the image and runs `postCreateCommand`. This takes a few
   minutes; subsequent starts are fast.
1. Run every Python sample's offline test suite from the repo root:

   ```bash
   pytest api_sample/python          # 292 tests, no network, no server
   ```

   VS Code's Test Explorer is wired to the same path (`python.testing.pytestArgs`).
1. To run a sample against a real server, copy `api_sample/.env.example` to
   `api_sample/.env`, fill it in, and from the sample's folder:

   ```bash
   python3 rest_list_cameras.py --env-file ../../.env --insecure
   ```

   `.env` is gitignored by [`api_sample/.gitignore`](../api_sample/.gitignore).
   `--insecure` is for the self-signed cert a local server presents.

If you edit `devcontainer.json`, the change does not apply until you rebuild:
Command Palette → **Dev Containers: Rebuild Container**.

### Reaching the Nx server

The container is on Docker's/Podman's bridge network and can reach LAN addresses
(`https://192.168.x.x:7001`) and the cloud relay directly. A server on the
**host itself** is not at `localhost` from in here — use
`host.docker.internal` (Docker Desktop) or `host.containers.internal` (Podman).

### Adding a toolchain

Node, for the `api_sample/node_js` and `api_sample/typescript` ports:

```jsonc
"features": {
  "ghcr.io/devcontainers/features/node:1": { "version": "22" }
}
```

Then rebuild. Same pattern for `dotnet` (C# samples) — and note that `cpp/` needs
Conan plus the Nx SDK, which is a bigger job than one feature.

## Fixed container paths

`workspaceMount` and `workspaceFolder` pin the checkout to
`/workspaces/nx_open_integrations` rather than letting Dev Containers derive
it from the local folder name. Claude Code's project memory directory is keyed
on that exact string, so a clone into a differently-named folder must not shift
it. Don't change it without updating
[`claude-home/.gitignore`](claude-home/.gitignore) to match.

## `claude-home/`

[`claude-home/`](claude-home/) is Claude Code's config directory inside the
container, pointed to by the `CLAUDE_CONFIG_DIR` environment variable set in
`devcontainer.json`. It replaces an earlier bind mount of the host's
`~/.claude`, which exposed every other project's credentials and transcripts to
this container.

Two things in it are versioned: [`settings.json`](claude-home/settings.json),
which declares the enabled plugins and the permission rules (pre-allowing the
read-only and test commands used here: `pytest`, `ruff`, `rg`, `jq`, `ffprobe`),
and this project's memory
(`projects/-workspaces-nx_open_integrations/memory/`, markdown only).
Everything else — credentials, session transcripts, caches, plugin checkouts and
`installed_plugins.json` — stays local to the checkout and is gitignored by
`claude-home/.gitignore`, which denies everything by default and re-allows only
those two paths.

`installed_plugins.json` in particular must stay out of source control: it
records absolute install paths, and a copy carried over from another machine
points at directories that do not exist here. Each checkout builds its own by
running the install step below.

Because `settings.json` is shared, anything you put in it applies to everyone
who clones the repo. Personal preferences belong in `settings.local.json`
alongside it, which stays gitignored.

Memory is meant to be staged, reviewed and committed like any other change —
once committed, it is a tracked file and safe. What `git clean` destroys is
memory written mid-session that has not been committed yet. The `.gitignore`
above un-ignores the memory markdown (that is what makes it committable), so it
sits in the untracked-but-not-ignored state: a plain `git clean -df` removes it,
no `-x` needed. `settings.json` denies `Bash(git clean:*)` for that reason.

All of this is **container-scoped by design**. A Claude Code session started on
the host, or in any container that does not set `CLAUDE_CONFIG_DIR`, does not see
`claude-home/` at all: it gets stock defaults, no project memory, no enabled
plugins, and none of the settings above. That is accepted rather than worked
around, nothing in the repo builds or runs on the host anyway. Work on this
repo from inside the dev container.

## One-time steps per checkout

These are not repeated on every rebuild — they persist in `claude-home/`, which
lives on the bind mount, part of this checkout. A second clone of the repo, even
on the same host, does not inherit any of this and must redo it.

1. Inside the container, run `/login` in a Claude Code session to authenticate.
1. Register the marketplace and install the plugins this project uses. `claude`
   is on `PATH` (installed by `post-create.sh`), so no path glob is needed:

   ```bash
   claude plugin marketplace add anthropics/claude-plugins-official
   claude plugin install superpowers@claude-plugins-official
   claude plugin install context7@claude-plugins-official
   claude plugin install claude-md-management@claude-plugins-official
   ```

   These are the plugins already listed under `enabledPlugins` in
   `claude-home/settings.json`; this step fetches the bits and writes the local
   `installed_plugins.json`. Verify with `claude plugin list`.
