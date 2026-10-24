import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.join(ROOT, "scripts")
README = os.path.join(ROOT, "README.md")
AGENTS = os.path.join(ROOT, "AGENTS.md")

results = []


def check(name, condition, detail=""):
    ok = bool(condition)
    results.append(ok)
    if ok:
        print("[PASS] " + name)
    else:
        print("[FAIL] " + name + (": " + detail if detail else ""))


def read_text(path):
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


readme = read_text(README)
agents = read_text(AGENTS)

check("README.md exists", readme is not None, README + " is missing")
check("AGENTS.md exists", agents is not None, AGENTS + " is missing")

if readme is not None:
    lower = readme.lower()
    for keyword in ("install", "start", "test"):
        check(
            'README.md contains "' + keyword + '" (case-insensitive)',
            keyword in lower,
            "keyword not found in README.md",
        )
else:
    for keyword in ("install", "start", "test"):
        check('README.md contains "' + keyword + '" (case-insensitive)', False, "README.md missing")

if agents is not None:
    lower_a = agents.lower()
    for keyword in ("FastAPI", "Next.js", "Playwright"):
        check(
            'AGENTS.md mentions "' + keyword + '" (case-insensitive)',
            keyword.lower() in lower_a,
            "keyword not found in AGENTS.md",
        )
else:
    for keyword in ("FastAPI", "Next.js", "Playwright"):
        check('AGENTS.md mentions "' + keyword + '" (case-insensitive)', False, "AGENTS.md missing")

script_refs = []
if readme is not None:
    script_refs = re.findall(r"[A-Za-z0-9_./\\-]*scripts[\\/]+[A-Za-z0-9_.-]+\.(?:ps1|sh)", readme)

check(
    "README.md references at least one scripts/ .ps1 or .sh file",
    len(script_refs) > 0,
    "no script references found",
)

actual_scripts = set()
if os.path.isdir(SCRIPTS_DIR):
    actual_scripts = {name for name in os.listdir(SCRIPTS_DIR) if name.endswith((".ps1", ".sh"))}

for ref in sorted(set(script_refs)):
    name = re.split(r"[\\/]", ref)[-1]
    check(
        "README script reference scripts/" + name + " exists in scripts/",
        name in actual_scripts,
        "referenced script " + ref + " not found; scripts/ contains " + str(sorted(actual_scripts)),
    )

print("SUMMARY: " + str(sum(results)) + "/" + str(len(results)) + " checks passed")
sys.exit(0 if all(results) else 1)
