"""Tool allow-lists, argument validation, max steps and max cost per run."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from pipeline_health_agent.data import PIPELINES

READ_TOOLS = frozenset(
    {
        "get_pipeline_metrics",
        "search_logs",
        "get_recent_deploys",
        "lookup_incidents",
    }
)
WRITE_TOOLS = frozenset({"restart_consumer", "scale_partitions", "open_ticket"})

# Which tools each graph step may call.
STEP_ALLOWLIST: dict[str, frozenset[str]] = {
    "triage": frozenset({"get_pipeline_metrics", "lookup_incidents"}),
    "investigate": frozenset({"search_logs", "get_recent_deploys"}),
    "diagnose": frozenset(),  # model only
    "propose": frozenset(),
    "await_approval": frozenset(),
    "remediate": WRITE_TOOLS,
    "remember": frozenset(),
    # MCP clients are outside the graph; they get the full tool surface.
    "mcp": READ_TOOLS | WRITE_TOOLS,
}


class GuardrailError(RuntimeError):
    """Raised when a guardrail blocks a tool call or budget overrun."""


@dataclass
class RunBudget:
    max_steps: int = 12
    max_cost_usd: float = 0.50
    steps_used: int = 0
    cost_usd: float = 0.0
    violations: list[str] = field(default_factory=list)

    @classmethod
    def from_env(cls) -> RunBudget:
        return cls(
            max_steps=int(os.environ.get("PHA_MAX_STEPS", "12")),
            max_cost_usd=float(os.environ.get("PHA_MAX_COST_USD", "0.50")),
        )

    def record_step(self, step: str) -> None:
        self.steps_used += 1
        if self.steps_used > self.max_steps:
            msg = f"max steps exceeded ({self.steps_used}/{self.max_steps}) at {step}"
            self.violations.append(msg)
            raise GuardrailError(msg)

    def record_cost(self, amount: float) -> None:
        self.cost_usd += amount
        if self.cost_usd > self.max_cost_usd:
            msg = f"max cost exceeded (${self.cost_usd:.4f}/${self.max_cost_usd:.2f})"
            self.violations.append(msg)
            raise GuardrailError(msg)


_BUDGET: RunBudget | None = None


def reset_budget(budget: RunBudget | None = None) -> RunBudget:
    global _BUDGET
    _BUDGET = budget or RunBudget.from_env()
    return _BUDGET


def get_budget() -> RunBudget:
    global _BUDGET
    if _BUDGET is None:
        _BUDGET = RunBudget.from_env()
    return _BUDGET


def assert_tool_allowed(step: str, tool_name: str) -> None:
    allowed = STEP_ALLOWLIST.get(step)
    if allowed is None:
        raise GuardrailError(f"Unknown step {step!r}; no tool allow-list.")
    if tool_name not in allowed:
        raise GuardrailError(
            f"Tool {tool_name!r} is not allowed in step {step!r}. Allowed: {sorted(allowed)}"
        )


def validate_pipeline(pipeline: str) -> str:
    if pipeline not in PIPELINES:
        raise GuardrailError(f"Invalid pipeline {pipeline!r}. Choose from {PIPELINES}.")
    return pipeline


def validate_partitions(partitions: int) -> int:
    if not isinstance(partitions, int) or isinstance(partitions, bool):
        raise GuardrailError("partitions must be an int")
    if partitions < 2 or partitions > 64:
        raise GuardrailError("partitions must be between 2 and 64")
    return partitions


def validate_limit(limit: int, *, lo: int = 1, hi: int = 100) -> int:
    if not isinstance(limit, int) or isinstance(limit, bool):
        raise GuardrailError("limit must be an int")
    if limit < lo or limit > hi:
        raise GuardrailError(f"limit must be between {lo} and {hi}")
    return limit


def validate_summary(summary: str) -> str:
    if not isinstance(summary, str) or not summary.strip():
        raise GuardrailError("summary must be a non-empty string")
    if len(summary) > 2000:
        raise GuardrailError("summary too long (max 2000 chars)")
    return summary
