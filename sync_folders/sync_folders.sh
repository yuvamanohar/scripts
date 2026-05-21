#!/usr/bin/env bash
# Author: Yuva

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
VENV_DIR=${SYNC_FOLDERS_VENV:-"$SCRIPT_DIR/.venv"}
PYTHON_BIN="$VENV_DIR/bin/python"
USE_CAFFEINATE=${SYNC_FOLDERS_CAFFEINATE:-1}
CAFFEINATE_FLAGS=${SYNC_FOLDERS_CAFFEINATE_FLAGS:-"-ims"}

if [[ ! -x "$PYTHON_BIN" ]]; then
  BOOTSTRAP_PYTHON=${SYNC_FOLDERS_BOOTSTRAP_PYTHON:-python3}
  "$BOOTSTRAP_PYTHON" -m venv "$VENV_DIR"
fi

if [[ "$USE_CAFFEINATE" != "0" && "$USE_CAFFEINATE" != "false" && "$USE_CAFFEINATE" != "FALSE" ]]; then
  if command -v caffeinate >/dev/null 2>&1; then
    read -r -a CAFFEINATE_ARGS <<< "$CAFFEINATE_FLAGS"
    exec caffeinate "${CAFFEINATE_ARGS[@]}" "$PYTHON_BIN" "$SCRIPT_DIR/sync_folders.py" "$@"
  fi

  echo "caffeinate not found; continuing without sleep prevention" >&2
fi

exec "$PYTHON_BIN" "$SCRIPT_DIR/sync_folders.py" "$@"
