#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="$HOME/.local/bin:$PATH"

(
  cd "$root/backend"
  if [ -x .venv/bin/python ]; then
    .venv/bin/python -m pytest -q tests
  else
    python3 -m pytest -q tests
  fi
)

(
  cd "$root/frontend"
  npm test -- --run
)
