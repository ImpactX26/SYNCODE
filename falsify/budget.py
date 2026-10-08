"""Budget and loop limit trackers for incident investigation."""

from __future__ import annotations

import time
from typing import Optional, Tuple
from pydantic import BaseModel, Field

from falsify.state import IncidentState


class BudgetConfig(BaseModel):
    """Execution constraints and budget limits."""

    max_llm_calls: int = Field(default=20, description="Maximum total LLM calls allowed per incident")
    max_tool_calls: int = Field(default=15, description="Maximum total tool executions allowed per incident")
    max_elapsed_sec: float = Field(default=300.0, description="Maximum wall-clock execution time in seconds (5 mins)")
    max_iterations: int = Field(default=3, description="Maximum recovery/investigation loop iterations allowed")
    recursion_limit: int = Field(default=25, description="LangGraph recursion limit")


class BudgetTracker(BaseModel):
    """Runtime tracking of resource consumption against budget limits."""

    config: BudgetConfig = Field(default_factory=BudgetConfig)
    llm_calls: int = Field(default=0)
    tool_calls: int = Field(default=0)
    start_time: float = Field(default_factory=time.time)
    iterations: int = Field(default=0)

    def record_llm_call(self) -> None:
        """Increment LLM call counter."""
        self.llm_calls += 1

    def record_tool_call(self) -> None:
        """Increment tool call counter."""
        self.tool_calls += 1

    def record_iteration(self) -> None:
        """Increment loop iteration counter."""
        self.iterations += 1

    def is_exceeded(self) -> bool:
        """Check whether any budget constraint has been exceeded."""
        elapsed = time.time() - self.start_time
        if self.llm_calls >= self.config.max_llm_calls:
            return True
        if self.tool_calls >= self.config.max_tool_calls:
            return True
        if elapsed >= self.config.max_elapsed_sec:
            return True
        if self.iterations >= self.config.max_iterations:
            return True
        return False

    def get_exhaustion_reason(self) -> Optional[str]:
        """Return human-readable reason if budget is exceeded."""
        elapsed = time.time() - self.start_time
        if self.llm_calls >= self.config.max_llm_calls:
            return f"LLM call budget exhausted: {self.llm_calls}/{self.config.max_llm_calls} calls executed."
        if self.tool_calls >= self.config.max_tool_calls:
            return f"Tool call budget exhausted: {self.tool_calls}/{self.config.max_tool_calls} tools executed."
        if elapsed >= self.config.max_elapsed_sec:
            return f"Elapsed time budget exhausted: {elapsed:.1f}s >= {self.config.max_elapsed_sec}s limit."
        if self.iterations >= self.config.max_iterations:
            return f"Maximum loop iterations reached: {self.iterations}/{self.config.max_iterations} iterations executed."
        return None

    def check_and_enforce_budget(self, state: IncidentState) -> Tuple[bool, Optional[str]]:
        """Check budget constraints and escalate state if budget is exceeded.
        
        Returns:
            (is_exceeded, reason)
        """
        if self.is_exceeded():
            reason = self.get_exhaustion_reason() or "Execution budget exhausted."
            if reason not in state.errors:
                state.errors.append(f"Budget exceeded: {reason}")
            state.decision = "escalate"
            return True, reason
        return False, None
