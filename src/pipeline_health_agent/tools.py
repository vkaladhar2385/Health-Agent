"""Read and simulated write tools over the synthetic pipeline scenario."""

from __future__ import annotations

from pipeline_health_agent.data import Scenario, Snapshot
from pipeline_health_agent.memory import IncidentStore

_scenario: Scenario | None = None
_store: IncidentStore | None = None


def bind_scenario(scenario: Scenario) -> None:
    global _scenario
    _scenario = scenario


def bind_store(store: IncidentStore) -> None:
    global _store
    _store = store


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


def lookup_incidents(pipeline: str, limit: int = 5) -> list[dict[str, str | int]]:
    """Return past incidents for one pipeline from incident memory."""
    store = _require_store()
    return [incident.as_dict() for incident in store.lookup(pipeline, limit=limit)]


def restart_consumer(pipeline: str) -> dict[str, str]:
    """Simulate restarting the consumer for one pipeline. Write action."""
    _snapshot(pipeline)
    return {
        "action": "restart_consumer",
        "pipeline": pipeline,
        "status": "simulated_ok",
        "detail": f"Restarted {pipeline}-worker consumer group. Lag should drain after catch-up.",
    }


def scale_partitions(pipeline: str, partitions: int = 6) -> dict[str, str | int]:
    """Simulate scaling topic partitions. Write action."""
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
