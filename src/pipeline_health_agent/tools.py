"""Read-only tools over the synthetic pipeline scenario."""

from __future__ import annotations

from pipeline_health_agent.data import Scenario, Snapshot

_scenario: Scenario | None = None


def bind_scenario(scenario: Scenario) -> None:
    global _scenario
    _scenario = scenario


def get_pipeline_metrics(pipeline: str) -> dict[str, float | int | str]:
    """Return the latest metrics for one pipeline."""
    snapshot = _snapshot(pipeline)
    return {"pipeline": snapshot.pipeline, "role": snapshot.role, **snapshot.metrics}


def search_logs(pipeline: str, query: str = "", limit: int = 20) -> list[str]:
    """Return recent log lines, optionally filtered by a case-insensitive query."""
    snapshot = _snapshot(pipeline)
    matched = [line for line in snapshot.logs if query.lower() in line.lower()]
    return matched[:limit]


def get_recent_deploys(pipeline: str, limit: int = 5) -> list[dict[str, str]]:
    """Return the newest deploys for one pipeline."""
    snapshot = _snapshot(pipeline)
    return [deploy.as_dict() for deploy in snapshot.deploys[:limit]]


def _snapshot(pipeline: str) -> Snapshot:
    if _scenario is None:
        raise RuntimeError("No scenario is bound. Call bind_scenario() before using tools.")
    try:
        return _scenario.snapshots[pipeline]
    except KeyError:
        known = ", ".join(_scenario.snapshots)
        raise ValueError(f"Unknown pipeline {pipeline!r}. Choose from {known}.") from None
