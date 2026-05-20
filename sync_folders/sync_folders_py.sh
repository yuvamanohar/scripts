#!/usr/bin/env bash
# Author: Yuva

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
VENV_DIR=${SYNC_FOLDERS_VENV:-"$SCRIPT_DIR/.venv"}
PYTHON_BIN="$VENV_DIR/bin/python"

if [[ ! -x "$PYTHON_BIN" ]]; then
  BOOTSTRAP_PYTHON=${SYNC_FOLDERS_BOOTSTRAP_PYTHON:-python3}
  "$BOOTSTRAP_PYTHON" -m venv "$VENV_DIR"
fi

exec "$PYTHON_BIN" "$SCRIPT_DIR/sync_folders.py" "$@"
