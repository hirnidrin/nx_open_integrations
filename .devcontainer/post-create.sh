#!/usr/bin/env bash
# Runs once, on container create (and again on every rebuild). Everything it
# writes lives outside the bind mount — ~/.venv-tools and ~/.local/bin — so a
# rebuild recreates it and the repo checkout stays clean.
#
# Idempotent: safe to re-run by hand after editing requirements-dev.txt.
set -euo pipefail

DEVCONTAINER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$HOME/.venv-tools"

echo "==> apt packages"
export DEBIAN_FRONTEND=noninteractive
sudo apt-get update -y
sudo apt-get install -y --no-install-recommends \
    python3 \
    python3-venv \
    python3-pip \
    ripgrep \
    jq \
    ffmpeg \
    iputils-ping \
    netcat-openbsd
# python3/python3-venv/python3-pip: noble ships 3.12.3, matching the Nx server.
# ripgrep, jq: fast code/JSON search.
# ffmpeg: ffprobe the clips media-http-stream saves, and generate a test video
#         to feed virtual-camera-upload.
# ping, nc: is the server reachable at all, before blaming the sample.
sudo rm -rf /var/lib/apt/lists/*

echo "==> tool venv at $VENV"
# Ubuntu marks its system python as externally managed (PEP 668), so pip must
# not install into it. One venv outside the workspace serves every sample.
if [ ! -x "$VENV/bin/python" ]; then
    python3 -m venv "$VENV"
fi
"$VENV/bin/python" -m pip install --upgrade pip
"$VENV/bin/python" -m pip install -r "$DEVCONTAINER_DIR/requirements-dev.txt"

echo "==> Claude Code CLI"
# Native install (no Node.js in this image); lands in ~/.local/bin, which
# devcontainer.json puts on PATH. Non-fatal: a network hiccup here should not
# fail the whole container build.
if command -v claude >/dev/null 2>&1; then
    echo "already installed: $(command -v claude)"
elif curl -fsSL https://claude.ai/install.sh | bash; then
    echo "installed"
else
    echo "WARNING: Claude Code CLI install failed; rerun this script or install it by hand." >&2
fi

echo
echo "==> versions"
python3 --version
"$VENV/bin/python" -m pytest --version
command -v claude >/dev/null 2>&1 && claude --version || true
echo
echo "Ready. Offline test suites, from the repo root:"
echo "    pytest api_sample/python"
