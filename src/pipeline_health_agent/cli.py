"""Command line for the pipeline health agent."""

from __future__ import annotations

import argparse
import json
import sys

from pipeline_health_agent.data import FAULTS, PIPELINES
from pipeline_health_agent.graph import resume_diagnosis, start_diagnosis
from pipeline_health_agent.memory import IncidentStore


def main(argv: list[str] | None = None) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(prog="pha")
    subcommands = parser.add_subparsers(dest="command", required=True)

    diagnose = subcommands.add_parser(
        "diagnose",
        help="Diagnose one mock pipeline and pause for write-action approval",
    )
    diagnose.add_argument("--pipeline", required=True, choices=PIPELINES)
    diagnose.add_argument(
        "--fault",
        default="consumer_lag_spike",
        choices=FAULTS,
        help="Fault to inject into that pipeline (default: consumer_lag_spike)",
    )
    diagnose.add_argument(
        "--decision",
        choices=("approve", "reject"),
        help="If set, approve or reject in the same process after the pause",
    )

    resume = subcommands.add_parser(
        "resume",
        help="Resume a paused run after human approval or rejection",
    )
    resume.add_argument("--thread", required=True, help="Thread id printed when diagnose paused")
    resume.add_argument("--decision", required=True, choices=("approve", "reject"))

    memory = subcommands.add_parser("memory", help="Show saved incidents")
    memory.add_argument("--pipeline", choices=PIPELINES, help="Filter by pipeline")

    args = parser.parse_args(argv)

    try:
        if args.command == "diagnose":
            _cmd_diagnose(args.pipeline, args.fault, args.decision)
        elif args.command == "resume":
            _cmd_resume(args.thread, args.decision)
        elif args.command == "memory":
            _cmd_memory(args.pipeline)
        else:
            parser.error(f"Unknown command {args.command}")
    except (RuntimeError, ValueError) as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1) from exc


def _cmd_diagnose(pipeline: str, fault: str, decision: str | None) -> None:
    thread_id, result = start_diagnosis(pipeline, fault)
    state = result.get("state") or {}
    print(f"pipeline: {pipeline}")
    print(f"injected fault: {fault}")
    print(f"thread: {thread_id}")
    print()
    _print_section("triage", state.get("triage"))
    _print_section("investigation", state.get("investigation"))
    _print_section("diagnosis", state.get("diagnosis"))

    if result["status"] != "paused":
        _print_completed(result)
        return

    proposal = result["interrupt"]["proposed_action"]
    print("proposed write action (waiting for human approval):")
    print(json.dumps(proposal, indent=2))
    print()
    print("Approve with:")
    print(f"  uv run pha resume --thread {thread_id} --decision approve")
    print("Or reject with:")
    print(f"  uv run pha resume --thread {thread_id} --decision reject")

    if decision:
        print()
        print(f"applying --decision {decision} ...")
        finished = resume_diagnosis(thread_id, decision)  # type: ignore[arg-type]
        _print_completed(finished)


def _cmd_resume(thread_id: str, decision: str) -> None:
    finished = resume_diagnosis(thread_id, decision)  # type: ignore[arg-type]
    print(f"thread: {thread_id}")
    print(f"decision: {decision}")
    print()
    _print_completed(finished)


def _cmd_memory(pipeline: str | None) -> None:
    store = IncidentStore()
    pipelines = [pipeline] if pipeline else list(PIPELINES)
    found = False
    for name in pipelines:
        incidents = store.lookup(name, limit=20)
        if not incidents:
            continue
        found = True
        print(f"## {name}")
        for incident in incidents:
            print(json.dumps(incident.as_dict(), indent=2))
            print()
    if not found:
        print("No incidents saved yet.")


def _print_completed(result: dict) -> None:
    state = result.get("state") or {}
    print(f"status: {result.get('status')}")
    print(f"decision: {state.get('decision')}")
    if state.get("remediation_result"):
        print("remediation:")
        print(json.dumps(state["remediation_result"], indent=2))
    print(f"incident_id: {state.get('incident_id')}")
    print()
    print("Incident saved to memory. Inspect with: uv run pha memory")


def _print_section(title: str, body: object) -> None:
    print(f"{title}:")
    print(body or "(pending)")
    print()


if __name__ == "__main__":
    main()
