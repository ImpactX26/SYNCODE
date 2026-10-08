"""Budget and loop limit trackers for incident investigation."""

from __future__ import annotations

import time
from typing import Optional
from pydantic import BaseModel, Field


class BudgetConfig(BaseModel):
    """Execution constraints and budget limits."""

    max_llm_calls: int = Field(default=20, description="Maximum total LLM calls allowed per incident")
    max_tool_calls: int = Field(default=30, description="Maximum total tool executions allowed per incident")
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
