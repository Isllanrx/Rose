"""Quality ratchet: fail when mypy errors or reported Ruff violations grow.

The project carries existing debt (mypy errors, log.error without traceback, ...).
Blocking on all of it would stop every change, and a report nobody reads lets it
grow. This gate compares today's counts with .github/quality-baseline.json and fails
only when a count goes up. When a count goes down, lower the baseline with --update
in the same change so the improvement cannot be lost.

Usage:
    python scripts/quality_gate.py            # check (CI)
    python scripts/quality_gate.py --update   # rewrite the baseline with current counts
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / ".github" / "quality-baseline.json"

# Ruff rules with existing violations: reported and ratcheted, not blocking.
RATCHET_RULES = [
    "TRY400",   # log.error without traceback
    "B904",     # raise without from inside except
    "B905",     # zip() without strict=
    "T201",     # print in production code
    "PLW0603",  # global statement
    "PLW1514",  # open() without encoding
    "SIM115",   # open() without a context manager
    "F841",     # unused local variable
    "PGH003",   # blanket type: ignore
    "ERA001",   # commented-out code
]


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")


def ruff_counts() -> dict[str, int]:
    result = run([sys.executable, "-m", "ruff", "check", ".", "--preview",
                  "--select", ",".join(RATCHET_RULES), "--output-format", "json", "--exit-zero"])
    if result.returncode != 0:
        sys.exit(f"ruff failed to run:\n{result.stderr}")
    counts = Counter(item["code"] for item in json.loads(result.stdout or "[]"))
    return {rule: counts.get(rule, 0) for rule in RATCHET_RULES}


def mypy_count() -> int:
    result = run([sys.executable, "-m", "mypy", "."])
    if result.returncode not in (0, 1):  # 2 means mypy itself failed
        sys.exit(f"mypy failed to run:\n{result.stdout}\n{result.stderr}")
    return sum(1 for line in result.stdout.splitlines() if re.search(r": error: ", line))


def main() -> int:
    mypy_now = mypy_count()
    ruff_now = ruff_counts()
    current = {"mypy": mypy_now, "ruff": ruff_now}

    if "--update" in sys.argv:
        BASELINE.parent.mkdir(exist_ok=True)
        BASELINE.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"Baseline written to {BASELINE.relative_to(ROOT)}")
        print(json.dumps(current, indent=2, sort_keys=True))
        return 0

    if not BASELINE.exists():
        print(f"Missing {BASELINE.relative_to(ROOT)}; run with --update to create it.")
        return 1
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))

    pairs = [("mypy errors", mypy_now, baseline.get("mypy", 0))]
    pairs += [(f"ruff {rule}", ruff_now[rule], baseline.get("ruff", {}).get(rule, 0))
              for rule in RATCHET_RULES]

    worse, better = [], []
    for name, now, base in pairs:
        marker = "  "
        if now > base:
            worse.append(name)
            marker = "!!"
        elif now < base:
            better.append(name)
            marker = "++"
        print(f"{marker} {name:<20} {now:>5}  (baseline {base})")

    if better:
        print("\nImproved: " + ", ".join(better)
              + ". Run `python scripts/quality_gate.py --update` to lock it in.")
    if worse:
        print("\nFAILED: new violations in " + ", ".join(worse)
              + ". Fix them, or run the tool locally to see where they are.")
        return 1
    print("\nQuality gate passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
