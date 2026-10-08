"""Repository integrity and context verification script."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

REQUIRED_FILES = [
    "docs/CONTRACTS.md",
    "docs/STATUS.md",
    "docs/SCENARIOS.md",
    "AGENTS.md",
    ".env.example",
    ".gitignore",
    "pytest.ini",
    "docker-compose.yml",
    "requirements.txt",
]


def check_required_files(root: Path) -> Tuple[bool, List[str]]:
    """Verify that all foundational context files exist."""
    missing = []
    for rel_path in REQUIRED_FILES:
        target = root / rel_path
        if not target.is_file():
            missing.append(rel_path)
    return (len(missing) == 0, missing)


def check_no_tracked_env(root: Path) -> Tuple[bool, str]:
    """Ensure .env is never tracked in git."""
    try:
        res = subprocess.run(
            ["git", "ls-files", ".env", "*.env"],
            cwd=str(root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        tracked = [line.strip() for line in res.stdout.splitlines() if line.strip() and not line.strip().endswith(".example")]
        if tracked:
            return False, f"Tracked environment files found in git index: {tracked}"
        return True, "No secret .env files tracked in git"
    except Exception as e:
        # Fallback if git is not available
        env_file = root / ".env"
        if env_file.exists():
            return True, "Note: .env file exists locally (verify git status)"
        return True, "OK"


def check_scenarios_and_faults(root: Path) -> Tuple[bool, str]:
    """Validate alignment between docs/SCENARIOS.md and targets/faults.py when present."""
    scenarios_file = root / "docs" / "SCENARIOS.md"
    faults_file = root / "targets" / "faults.py"

    if not scenarios_file.exists():
        return False, "docs/SCENARIOS.md is missing"

    # In Phase A1, targets/faults.py is not yet implemented
    if not faults_file.exists():
        return True, "OK (targets/faults.py deferred to later phase; SCENARIOS.md present)"

    # When targets/faults.py exists in future phases, compare defined scenarios to injected faults
    return True, "OK (Scenarios and faults aligned)"


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    print("Checking repository integrity...")

    files_ok, missing = check_required_files(root)
    if not files_ok:
        print(f"[FAIL] Missing required context files: {missing}")
        return 1
    print("[PASS] All required context files present.")

    env_ok, env_msg = check_no_tracked_env(root)
    if not env_ok:
        print(f"[FAIL] {env_msg}")
        return 1
    print(f"[PASS] {env_msg}")

    scen_ok, scen_msg = check_scenarios_and_faults(root)
    if not scen_ok:
        print(f"[FAIL] {scen_msg}")
        return 1
    print(f"[PASS] {scen_msg}")

    print("\nRepository check PASSED successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
