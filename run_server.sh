#!/usr/bin/env bash
set -euo pipefail

# Default: listen on all interfaces so phone browsers can reach it
HOST="0.0.0.0"
PORT="8080"

# Simple arg parsing
while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) HOST="$2"; shift 2;;
    --port) PORT="$2"; shift 2;;
    *) echo "Unknown arg: $1"; exit 1;;
  esac
done

# Activate venv if present
if [[ -f ".venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

export FLASK_APP=web/app.py
export FLASK_ENV=production

python -m flask run --host "${HOST}" --port "${PORT}"
