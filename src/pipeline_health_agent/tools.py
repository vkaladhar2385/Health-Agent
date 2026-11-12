"""Read and simulated write tools over the synthetic pipeline scenario."""

from __future__ import annotations

from pipeline_health_agent.data import Scenario, Snapshot
from pipeline_health_agent.guardrails import (
    assert_tool_allowed,
    validate_limit,
    validate_partitions,
    validate_pipeline,
    validate_summary,
)
from pipeline_health_agent.memory import IncidentStore
from pipeline_health_agent.observability import timed_span

_scenario: Scenario | None = None
_store: IncidentStore | None = None
_current_step: str = "triage"


def bind_scenario(scenario: Scenario) -> None:
    global _scenario
    _scenario = scenario


def bind_store(store: IncidentStore) -> None:
    global _store
    _store = store


def set_tool_step(step: str) -> None:
    global _current_step
    _current_step = step


def get_pipeline_metrics(pipeline: str) -> dict[str, float | int | str]:
    """Return the latest metrics for one pipeline."""
    assert_tool_allowed(_current_step, "get_pipeline_metrics")
    pipeline = validate_pipeline(pipeline)
    with timed_span("tool", "get_pipeline_metrics", pipeline=pipeline):
        snapshot = _snapshot(pipeline)
        return {"pipeline": snapshot.pipeline, "role": snapshot.role, **snapshot.metrics}


def search_logs(pipeline: str, query: str = "", limit: int = 20) -> list[str]:
    """Return recent log lines, optionally filtered by a case-insensitive query."""
    assert_tool_allowed(_current_step, "search_logs")
    pipeline = validate_pipeline(pipeline)
    limit = validate_limit(limit)
    with timed_span("tool", "search_logs", pipeline=pipeline, query=query, limit=limit):
        snapshot = _snapshot(pipeline)
        matched = [line for line in snapshot.logs if query.lower() in line.lower()]
        return matched[:limit]


def get_recent_deploys(pipeline: str, limit: int = 5) -> list[dict[str, str]]:
    """Return the newest deploys for one pipeline."""
    assert_tool_allowed(_current_step, "get_recent_deploys")
    pipeline = validate_pipeline(pipeline)
    limit = validate_limit(limit, hi=50)
    with timed_span("tool", "get_recent_deploys", pipeline=pipeline, limit=limit):
        snapshot = _snapshot(pipeline)
        return [deploy.as_dict() for deploy in snapshot.deploys[:limit]]


def lookup_incidents(pipeline: str, limit: int = 5) -> list[dict[str, str | int]]:
    """Return past incidents for one pipeline from incident memory."""
    assert_tool_allowed(_current_step, "lookup_incidents")
    pipeline = validate_pipeline(pipeline)
    limit = validate_limit(limit, hi=50)
    with timed_span("tool", "lookup_incidents", pipeline=pipeline, limit=limit):
        store = _require_store()
        return [incident.as_dict() for incident in store.lookup(pipeline, limit=limit)]


def restart_consumer(pipeline: str) -> dict[str, str]:
    """Simulate restarting the consumer for one pipeline. Write action."""
    assert_tool_allowed(_current_step, "restart_consumer")
    pipeline = validate_pipeline(pipeline)
    with timed_span("tool", "restart_consumer", pipeline=pipeline):
        _snapshot(pipeline)
        return {
            "action": "restart_consumer",
            "pipeline": pipeline,
            "status": "simulated_ok",
            "detail": f"Restarted {pipeline}-worker consumer group. Lag should drain after catch-up.",
        }


def scale_partitions(pipeline: str, partitions: int = 6) -> dict[str, str | int]:
    """Simulate scaling topic partitions. Write action."""
    assert_tool_allowed(_current_step, "scale_partitions")
    pipeline = validate_pipeline(pipeline)
    partitions = validate_partitions(partitions)
    with timed_span("tool", "scale_partitions", pipeline=pipeline, partitions=partitions):
        _snapshot(pipeline)
        return {
            "action": "scale_partitions",
            "pipeline": pipeline,
            "partitions": partitions,
            "status": "simulated_ok",
            "detail": f"Scaled {pipeline} topic to {partitions} partitions (simulated).",
        }


def open_ticket(pipeline: str, summary: str) -> dict[str, str]:
    """Simulate opening an incident ticket. Write action."""
    assert_tool_allowed(_current_step, "open_ticket")
    pipeline = validate_pipeline(pipeline)
    summary = validate_summary(summary)
    with timed_span("tool", "open_ticket", pipeline=pipeline):
        _snapshot(pipeline)
        return {
            "action": "open_ticket",
            "pipeline": pipeline,
            "status": "simulated_ok",
            "ticket_id": f"PHA-{pipeline.upper()}-001",
            "summary": summary,
            "detail": "Ticket opened in the simulated tracker.",
        }


def _snapshot(pipeline: str) -> Snapshot:
    if _scenario is None:
        raise RuntimeError("No scenario is bound. Call bind_scenario() before using tools.")
    try:
        return _scenario.snapshots[pipeline]
    except KeyError:
        known = ", ".join(_scenario.snapshots)
        raise ValueError(f"Unknown pipeline {pipeline!r}. Choose from {known}.") from None


def _require_store() -> IncidentStore:
    if _store is None:
        raise RuntimeError("No incident store is bound. Call bind_store() first.")
    return _store
