#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="$HOME/.local/bin:$PATH"

uvicorn_bin="$root/backend/.venv/bin/uvicorn"
if [ ! -x "$uvicorn_bin" ]; then
  uvicorn_bin="uvicorn"
fi

cd "$root/backend"
nohup "$uvicorn_bin" app.main:app --reload >"$root/backend.log" 2>&1 &
backend_pid=$!

cd "$root/frontend"
nohup npm run dev >"$root/frontend.log" 2>&1 &
frontend_pid=$!

printf '{\n  "backend": %d,\n  "frontend": %d\n}\n' \
  "$backend_pid" "$frontend_pid" >"$root/scripts/dev-pids.json"

echo "Backend started (PID $backend_pid): http://localhost:8000"
echo "Frontend started (PID $frontend_pid): http://localhost:3000"
echo "Logs: $root/backend.log, $root/frontend.log"
echo "Stop with: $root/scripts/stop-dev.sh"
