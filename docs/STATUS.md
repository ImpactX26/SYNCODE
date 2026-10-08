# Project Status: Falsify

## Current Milestone: Phase A2 (Confidence Engine + LLM Wrapper)

### 1. What Changed (Phase A2)
- Implemented deterministic evidence-driven confidence calculation engine in `falsify/confidence.py`:
  - Added `get_leading_hypothesis` to prioritize active hypotheses by net supporting evidence.
  - Implemented strict evidence caps: `CAP_ZERO_SUPPORTING` (0.20), `CAP_CONTRADICTING` (0.40), `CAP_FEWER_THAN_TWO_SOURCES` (0.60), and `MAX_CONFIDENCE` (0.95).
  - Added source diversity weighting and bonus for falsified rival hypotheses.
  - Added state updater helper `update_state_confidence(state: IncidentState)`.
- Implemented resilient LLM client wrapper in `falsify/llm.py`:
  - Added environment variable configuration (`PRIMARY_MODEL`, `FALLBACK_MODEL`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `REPLAY`, `REPLAY_CACHE_DB`, `LLM_MAX_RETRIES`, `LLM_TIMEOUT_SEC`).
  - Added exponential backoff retry handler for transient HTTP 429, 5xx, and timeout errors.
  - Added automatic fallback model invocation when primary model retries are exhausted.
  - Added persistent SQLite replay cache with SHA-256 key hashing (`SQLiteReplayCache`).
  - Added `REPLAY=1` zero-network execution mode.
  - Added safe JSON extraction (`extract_and_parse_json`) handling markdown code fences and malformed responses.
  - Added `complete_pydantic` helper for structured schema validation.
- Expanded comprehensive unit test suites:
  - `tests/test_confidence.py` (11 tests covering all evidence caps, source diversity, rival falsification, and edge cases).
  - `tests/test_llm_fallback.py` (9 tests covering cache read/write, transient retries, fallback switching, replay mode, JSON parsing, and schema validation).

### 2. Tests Run & Validation
- Ran `python scripts/check_repo.py`: PASSED (Integrity verified, all required context files present, no secret .env files tracked).
- Ran `pytest -v`: PASSED (`37 passed in 0.34s`).
- Ran `python -c "import falsify.state"`: PASSED (`falsify.state imported successfully`).
- Ran `git status`: Verified working branch `reethu`.

### 3. Blockers / Risks
- None.

### 4. Next Step
- Phase A3: Implement LangGraph agent workflow nodes (`Triage`, `Hypothesis`, `Experiment`, `Skeptic`) in `falsify/graph.py`.

