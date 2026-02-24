#!/usr/bin/env bash
set -euo pipefail

echo "Attempting to start arduino-router (if present)"
if command -v systemctl >/dev/null 2>&1; then
  sudo systemctl start arduino-router.service || true
fi

echo "Done (ignored errors if service/process not present)."
