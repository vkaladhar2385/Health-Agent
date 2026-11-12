"""Compare Claude vs OpenAI on a small fixed scenario pack."""

from __future__ import annotations

import os
import sys

from pipeline_health_agent.evals.runner import CaseResult, _run_one, print_report
from pipeline_health_agent.evals.scenarios import SCENARIOS
from pipeline_health_agent.models import load_project_env


COMPARE_IDS = ("H01", "L01", "E01", "P01", "A01", "I01")


def main(argv: list[str] | None = None) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    load_project_env()
    selected = [s for s in SCENARIOS if s["id"] in COMPARE_IDS]
    providers = [
        ("anthropic", os.environ.get("PHA_MODEL", "claude-sonnet-5")),
        ("openai", os.environ.get("PHA_OPENAI_MODEL", "gpt-4o-mini")),
    ]
    exit_code = 0
    for provider, model in providers:
        if provider == "openai" and not os.environ.get("OPENAI_API_KEY", "").strip():
            print(f"SKIP provider={provider}: OPENAI_API_KEY not set")
            continue
        print(f"=== provider={provider} model={model} ===")
        os.environ["PHA_PROVIDER"] = provider
        os.environ["PHA_MODEL"] = model
        results: list[CaseResult] = [_run_one(s) for s in selected]
        code = print_report(results)
        exit_code = exit_code or code
        print()
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
