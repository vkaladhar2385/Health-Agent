"""Command line for the pipeline health agent."""

from __future__ import annotations

import argparse
import sys

from pipeline_health_agent.data import FAULTS, PIPELINES
from pipeline_health_agent.graph import run_diagnosis


def main(argv: list[str] | None = None) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(prog="pha")
    subcommands = parser.add_subparsers(dest="command", required=True)

    diagnose = subcommands.add_parser("diagnose", help="Diagnose one mock pipeline")
    diagnose.add_argument("--pipeline", required=True, choices=PIPELINES)
    diagnose.add_argument(
        "--fault",
        default="consumer_lag_spike",
        choices=FAULTS,
        help="Fault to inject into that pipeline (default: consumer_lag_spike)",
    )

    args = parser.parse_args(argv)
    if args.command != "diagnose":
        parser.error(f"Unknown command {args.command}")

    try:
        result = run_diagnosis(args.pipeline, args.fault)
    except (RuntimeError, ValueError) as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1) from exc

    print(f"pipeline: {args.pipeline}")
    print(f"injected fault: {args.fault}")
    print()
    print("triage:")
    print(result["triage"])
    print()
    print("investigation:")
    print(result["investigation"])
    print()
    print("diagnosis:")
    print(result["diagnosis"])


if __name__ == "__main__":
    main()
