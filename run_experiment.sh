#!/usr/bin/env bash
# CAPE-Pins one-command runner for Linux / WSL. Same arguments as run_experiment.cmd.
#   bash run_experiment.sh --stage smoke
# Note: this Windows workspace was validated with the native MinGW track; a Linux track needs
# its own venv (python3.12 -m venv .venv) and a g++ toolchain, created by scripts/bootstrap.py.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${CAPE_PYTHON:-python3.12}"
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "ERROR: $PY not found (install CPython 3.12 or set CAPE_PYTHON)" >&2
  exit 2
fi
exec "$PY" "$ROOT/run_all.py" "$@"
