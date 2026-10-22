import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

passed = 0
total = 0


def report(ok, name, expected, actual):
    global passed, total
    total += 1
    if ok:
        passed += 1
        print("[PASS] %s" % name)
    else:
        print("[FAIL] %s: expected %s got %s" % (name, expected, actual))


def read_text(rel):
    p = ROOT / rel
    if not p.is_file():
        return None
    return p.read_text(encoding="utf-8-sig")


start_dev = read_text("scripts/start-dev.ps1")
stop_dev = read_text("scripts/stop-dev.ps1")
test_ps = read_text("scripts/test.ps1")
gitignore = read_text(".gitignore")

report(
    start_dev is not None and "uvicorn" in start_dev and "npm run dev" in start_dev,
    "start-dev.ps1 exists and text contains both uvicorn and npm run dev",
    "file with 'uvicorn' and 'npm run dev'",
    "missing file" if start_dev is None
    else "missing: " + ", ".join(
        t for t in ("uvicorn", "npm run dev") if t not in start_dev
    ),
)

report(
    stop_dev is not None,
    "stop-dev.ps1 exists",
    "file",
    "missing file" if stop_dev is None else "file",
)

report(
    test_ps is not None and "pytest" in test_ps and "vitest" in test_ps,
    "test.ps1 exists and text contains both pytest and vitest",
    "file with 'pytest' and 'vitest'",
    "missing file" if test_ps is None
    else "missing: " + ", ".join(
        t for t in ("pytest", "vitest") if t not in test_ps
    ),
)

required_entries = ["node_modules", "__pycache__", ".venv", ".env", ".next"]
if gitignore is None:
    report(False, ".gitignore contains node_modules, __pycache__, .venv, .env, .next",
           "all entries", "missing file")
else:
    missing = [e for e in required_entries if e not in gitignore]
    report(
        not missing,
        ".gitignore contains node_modules, __pycache__, .venv, .env, .next",
        "all entries",
        "missing: " + ", ".join(missing) if missing else "none missing",
    )

report(
    (ROOT / "scripts").is_dir(),
    "scripts directory exists and is correctly named",
    "scripts/ directory",
    "missing scripts/ directory",
)

psroot_ok = test_ps is not None and "$PSScriptRoot" in test_ps
report(
    psroot_ok,
    "test.ps1 uses $PSScriptRoot so it works from outside the repo root",
    "$PSScriptRoot",
    "not found" if test_ps is not None else "missing file",
)

nonzero_ok = (
    test_ps is not None
    and "$LASTEXITCODE" in test_ps
    and "exit 1" in test_ps
)
report(
    nonzero_ok,
    "test.ps1 exits non-zero when a test command fails",
    "checks $LASTEXITCODE and exits 1",
    "not found" if test_ps is not None else "missing file",
)

print("SUMMARY: %d/%d passed" % (passed, total))
sys.exit(0 if passed == total else 1)
