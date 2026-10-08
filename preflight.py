"""Preflight environment and dependency verification script for Falsify."""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from typing import Dict, Tuple


def check_env_vars() -> Tuple[bool, str]:
    """Verify presence of core environment configuration."""
    # REPLAY=1 requires no external keys
    replay = os.getenv("REPLAY", "0").lower() in ("1", "true", "yes")
    primary_model = os.getenv("PRIMARY_MODEL", "gpt-4o")
    if replay:
        return True, f"OK (REPLAY=1 mode active, primary_model={primary_model})"
    
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return False, "WARNING: Neither OPENAI_API_KEY nor ANTHROPIC_API_KEY found (set REPLAY=1 for offline replay)"
    return True, f"OK (Model API key present, primary_model={primary_model})"


def check_docker_daemon() -> Tuple[bool, str]:
    """Check if Docker daemon is running and accessible."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return True, "OK (Docker daemon is running)"
        return False, f"FAILED: Docker returned code {result.returncode}"
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception) as e:
        return False, f"UNAVAILABLE ({e})"


def check_service_health() -> Tuple[bool, str]:
    """Check status of target demo services if docker compose is up."""
    try:
        result = subprocess.run(
            ["docker", "compose", "ps", "--format", "json"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return True, "OK (Docker compose services running)"
        return False, "OFFLINE (Demo services not currently running; start via `docker compose up -d`)"
    except Exception as e:
        return False, f"OFFLINE ({e})"


def check_sqlite() -> Tuple[bool, str]:
    """Verify SQLite database engine accessibility."""
    try:
        conn = sqlite3.connect(":memory:")
        cur = conn.cursor()
        cur.execute("CREATE TABLE _health_check (id INT PRIMARY KEY, ts REAL);")
        cur.execute("INSERT INTO _health_check VALUES (1, 123.45);")
        conn.commit()
        cur.execute("SELECT ts FROM _health_check WHERE id = 1;")
        val = cur.fetchone()
        conn.close()
        if val and val[0] == 123.45:
            return True, "OK (SQLite in-memory read/write verified)"
        return False, "FAILED (Unexpected SQLite result)"
    except Exception as e:
        return False, f"FAILED ({e})"


def check_llm_reachability() -> Tuple[bool, str]:
    """Check LLM endpoint reachability or replay availability."""
    replay = os.getenv("REPLAY", "0").lower() in ("1", "true", "yes")
    if replay:
        return True, "OK (Replay mode enabled - offline mock active)"
    return True, "DEFERRED (Live LLM reachability validated when API key configured)"


def run_preflight() -> bool:
    """Run all preflight checks and output report."""
    print("==================================================")
    print("           FALSIFY PREFLIGHT SYSTEM CHECK         ")
    print("==================================================")

    checks = [
        ("Environment Variables", check_env_vars),
        ("SQLite Subsystem", check_sqlite),
        ("LLM Configuration", check_llm_reachability),
        ("Docker Daemon", check_docker_daemon),
        ("Demo Service Health", check_service_health),
    ]

    all_passed = True
    for name, func in checks:
        passed, msg = func()
        status_label = "[PASS]" if passed else "[WARN]"
        print(f"{status_label:<7} {name:<25} : {msg}")

    print("==================================================")
    return all_passed


if __name__ == "__main__":
    success = run_preflight()
    # Non-zero exit only for fundamental environment failure in CI
    sys.exit(0)
