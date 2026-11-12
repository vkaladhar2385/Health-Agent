"""Offline Week 4 checks: guardrails, injection data, action policy."""

import pytest

from pipeline_health_agent.data import build_scenario
from pipeline_health_agent.graph import _choose_action
from pipeline_health_agent.guardrails import GuardrailError, assert_tool_allowed, validate_partitions
from pipeline_health_agent.tools import bind_scenario, get_pipeline_metrics, set_tool_step


def test_prompt_injection_metrics_stay_healthy() -> None:
    scenario = build_scenario("egress", "prompt_injection")
    snap = scenario.snapshots["egress"]
    assert snap.metrics["status"] == "healthy"
    assert any("IGNORE ALL PRIOR INSTRUCTIONS" in line for line in snap.logs)


def test_prompt_injection_policy_is_none() -> None:
    scenario = build_scenario("egress", "prompt_injection")
    snap = scenario.snapshots["egress"]
    action = _choose_action(
        {
            "pipeline": "egress",
            "metrics": snap.metrics,
            "logs": list(snap.logs),
            "diagnosis": "The pipeline is healthy.",
        }
    )
    assert action["action"] == "none"


def test_tool_allowlist_blocks_write_in_triage() -> None:
    with pytest.raises(GuardrailError):
        assert_tool_allowed("triage", "restart_consumer")


def test_partitions_validation() -> None:
    assert validate_partitions(6) == 6
    with pytest.raises(GuardrailError):
        validate_partitions(1)


def test_metrics_tool_works_in_triage_step() -> None:
    bind_scenario(build_scenario("egress", "none"))
    set_tool_step("triage")
    metrics = get_pipeline_metrics("egress")
    assert metrics["status"] == "healthy"
