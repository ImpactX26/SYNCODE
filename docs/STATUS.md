# Project Status: Falsify

## Current Milestone: Phase A1 (Skeleton, Context Kit, and CI)

### 1. What Changed (Phase A1)
- Created project directory layout (`falsify/`, `falsify/tools/`, `targets/`, `app/api/`, `app/dashboard/`, `tests/`, `eval/`, `demo/`, `docs/`, `scripts/`, `.github/workflows/`).
- Created foundational state models in `falsify/state.py` (`Evidence`, `Hypothesis`, `IncidentState`).
- Created tool foundation in `falsify/tools/base.py` (`ToolResult`, `safe_tool` decorator, and typed stubs: `get_metrics`, `get_logs`, `get_deploy_history`, `probe_dependency`, `get_db_stats`, `restart_service`, `rollback_deploy`, `scale_service`).
- Created foundation stubs for LangGraph orchestrator (`falsify/graph.py`), LLM client (`falsify/llm.py`), budget tracker (`falsify/budget.py`), decision gate (`falsify/gate.py`), confidence calculator (`falsify/confidence.py`), data sanitization (`falsify/sanitize.py`), and memory store (`falsify/memory.py`).
- Authored contract documentation (`docs/CONTRACTS.md`), scenario placeholder (`docs/SCENARIOS.md`), and agent operational guidelines (`AGENTS.md`).
- Configured environment and build files (`.env.example`, `.gitignore`, `requirements.txt`, `pytest.ini`, `docker-compose.yml`).
- Created repository check script (`scripts/check_repo.py`) and preflight script (`preflight.py`).
- Configured GitHub Actions CI workflow (`.github/workflows/ci.yml`) and pull request template (`.github/pull_request_template.md`).
- Authored 11 placeholder unit test suites in `tests/`.

### 2. Tests Run & Validation
- Ran `python scripts/check_repo.py`: PASSED (Integrity verified, all required context files present, no secret .env files tracked).
- Ran `pytest --collect-only`: PASSED (21 test functions collected across 11 test modules).
- Ran `pytest -q`: PASSED (`21 passed in 0.08s`).
- Ran `python -c "import falsify.state"`: PASSED (`falsify.state imported successfully`).
- Ran `preflight.py`: PASSED (Reported environment and dependencies with graceful warnings for optional/unconfigured local docker).
- Ran `git status`: Verified working branch `feat/a-skeleton` with clean staged index and untracked A1 files ready for commit.

### 3. Blockers / Risks
- None. All foundation schemas, scaffolding, and tooling contracts are verified.

### 4. Next Step
- Phase A2: Implement deterministic confidence calculation (`falsify/confidence.py`) and resilient LLM client with SQLite replay cache (`falsify/llm.py`).

