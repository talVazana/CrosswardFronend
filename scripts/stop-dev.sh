#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
pid_file="$root/scripts/dev-pids.json"

if [ ! -f "$pid_file" ]; then
  echo "No PID file at $pid_file"
  exit 0
fi

for name in backend frontend; do
  pid="$(sed -n "s/.*\"$name\": \([0-9][0-9]*\).*/\1/p" "$pid_file")"
  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
    echo "Stopped $name (PID $pid)"
  else
    echo "$name is not running"
  fi
done

rm -f "$pid_file"
