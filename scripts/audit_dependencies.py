"""Fail on any known vulnerability in pinned dependencies that is not an accepted exception.

Accepted exceptions live in .github/pip-audit-ignore.txt, one advisory ID per line with the
reason. The list may only shrink: an advisory that no longer applies (dependency upgraded)
is reported so the line can be removed in the same change.

Usage: python scripts/audit_dependencies.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IGNORE_FILE = ROOT / ".github" / "pip-audit-ignore.txt"
REQUIREMENTS = ["requirements.txt", "requirements-dev.txt"]


def accepted_ids() -> set[str]:
    ids = set()
    for line in IGNORE_FILE.read_text(encoding="utf-8").splitlines():
        advisory = line.split("#", 1)[0].strip()
        if advisory:
            ids.add(advisory)
    return ids


def main() -> int:
    cmd = [sys.executable, "-m", "pip_audit", "--progress-spinner", "off", "-f", "json"]
    for req in REQUIREMENTS:
        cmd += ["-r", req]
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError:
        print(f"pip-audit did not produce a report (exit {result.returncode}):\n{result.stderr}")
        return 1

    accepted = accepted_ids()
    found: dict[str, str] = {}
    for dep in report.get("dependencies", []):
        for vuln in dep.get("vulns", []):
            fixes = ", ".join(vuln.get("fix_versions") or []) or "no fix yet"
            found[vuln["id"]] = f"{dep['name']} {dep['version']} (fixed in {fixes})"

    new = sorted(set(found) - accepted)
    stale = sorted(accepted - set(found))

    print(f"{len(found)} known advisories, {len(accepted)} accepted exceptions")
    if stale:
        print("No longer affected, remove from .github/pip-audit-ignore.txt: " + ", ".join(stale))
    if new:
        print("NEW vulnerabilities (not accepted):")
        for advisory in new:
            print(f"  - {advisory}: {found[advisory]}")
        return 1
    print("Dependency audit passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
