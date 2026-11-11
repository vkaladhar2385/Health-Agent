"""Synthetic telemetry for three mock pipelines."""

from __future__ import annotations

from dataclasses import dataclass

PIPELINES = ("ingest", "stream", "egress")
FAULTS = ("none", "consumer_lag_spike")

ROLES = {
    "ingest": "Pulls source records onto the orders topic.",
    "stream": "Validates and enriches records on the orders topic.",
    "egress": "Consumes the orders topic and writes the warehouse table.",
}


@dataclass(frozen=True)
class Deploy:
    service: str
    version: str
    at: str
    change: str

    def as_dict(self) -> dict[str, str]:
        return {
            "service": self.service,
            "version": self.version,
            "at": self.at,
            "change": self.change,
        }


@dataclass(frozen=True)
class Snapshot:
    pipeline: str
    role: str
    metrics: dict[str, float | int | str]
    logs: tuple[str, ...]
    deploys: tuple[Deploy, ...]


@dataclass(frozen=True)
class Scenario:
    focus: str
    fault: str
    snapshots: dict[str, Snapshot]


def build_scenario(pipeline: str, fault: str = "consumer_lag_spike") -> Scenario:
    """Build all three pipelines, with the fault applied only to one of them."""
    _check(pipeline, fault)
    snapshots = {
        name: build_snapshot(name, fault if name == pipeline else "none")
        for name in PIPELINES
    }
    return Scenario(focus=pipeline, fault=fault, snapshots=snapshots)


def build_snapshot(pipeline: str, fault: str = "none") -> Snapshot:
    _check(pipeline, fault)
    if fault == "consumer_lag_spike":
        return _lag_spike(pipeline)
    return _healthy(pipeline)


def _check(pipeline: str, fault: str) -> None:
    if pipeline not in PIPELINES:
        raise ValueError(f"Unknown pipeline {pipeline!r}. Choose from {PIPELINES}.")
    if fault not in FAULTS:
        raise ValueError(f"Unknown fault {fault!r}. Choose from {FAULTS}.")
    if fault == "consumer_lag_spike" and pipeline == "ingest":
        raise ValueError("consumer_lag_spike applies to stream and egress, which have consumers.")


def _healthy(pipeline: str) -> Snapshot:
    service = f"{pipeline}-worker"
    return Snapshot(
        pipeline=pipeline,
        role=ROLES[pipeline],
        metrics={
            "status": "healthy",
            "throughput_per_sec": 1200,
            "error_rate": 0.001,
            "consumer_lag_seconds": 2,
            "consumer_lag_records": 40,
        },
        logs=(
            f"2026-10-29T18:10:00Z INFO {service} heartbeat ok",
            f"2026-10-29T18:11:00Z INFO {service} lag_records=40 lag_seconds=2 within threshold",
            f"2026-10-29T18:12:00Z INFO {service} processed 72000 records in the last minute",
        ),
        deploys=(
            Deploy(
                service=service,
                version="1.4.1",
                at="2026-10-28T15:00:00Z",
                change="routine release, no config change",
            ),
        ),
    )


def _lag_spike(pipeline: str) -> Snapshot:
    service = f"{pipeline}-worker"
    return Snapshot(
        pipeline=pipeline,
        role=ROLES[pipeline],
        metrics={
            "status": "degraded",
            "throughput_per_sec": 180,
            "error_rate": 0.004,
            "consumer_lag_seconds": 940,
            "consumer_lag_records": 18420,
        },
        logs=(
            f"2026-10-29T18:06:10Z INFO {service} started version 1.4.2",
            (
                f"2026-10-29T18:12:04Z WARN {service} consumer lag spike: "
                "lag_records=18420 lag_seconds=940 threshold_records=500"
            ),
            (
                f"2026-10-29T18:12:11Z ERROR {service} cannot keep up because "
                "max.poll.records was changed from 500 to 10"
            ),
            f"2026-10-29T18:12:40Z INFO {service} rebalance complete, processing_rate=180/s",
        ),
        deploys=(
            Deploy(
                service=service,
                version="1.4.2",
                at="2026-10-29T18:05:00Z",
                change="set max.poll.records from 500 to 10",
            ),
            Deploy(
                service=service,
                version="1.4.1",
                at="2026-10-28T15:00:00Z",
                change="routine release, no config change",
            ),
        ),
    )
