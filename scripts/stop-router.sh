#!/usr/bin/env bash
set -euo pipefail

echo "Attempting to stop arduino-router (if present)"
if command -v systemctl >/dev/null 2>&1; then
  sudo systemctl stop arduino-router.service || true
fi

# Fallback: try to kill processes named arduino-router
sudo pkill -f arduino-router || true
echo "Done (ignored errors if service/process not present)."
